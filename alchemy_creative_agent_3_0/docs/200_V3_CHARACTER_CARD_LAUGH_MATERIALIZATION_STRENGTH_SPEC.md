# Doc200 — Character Card Laugh Materialization Strength

Date: 2026-07-24

Status: superseded as implementation authority by Doc201. This document remains
the evidence record for the three failed MCP candidates and the discovery that
the previous laugh materialization language was too weak. The durable contract
source is Doc201's structured foundation laugh intent; prompt wording is only a
projection of that typed contract.

## 1. Problem

After Doc199 exposed expression-specific dimensions to shared Vision, fresh MCP
`expression.laugh` candidates were generated and reviewed through the correct
receipt path. The system no longer failed because of Brain, Provider/MCP, prompt
parity, reference parity, or missing Vision dimensions.

The remaining failure was semantic strength: candidates were technically clean,
same-person, well framed, and realistic, but they read as attractive open-mouth
smiles rather than a reliable laugh keyframe. Shared Vision correctly reported
weak periocular participation, cheek/jaw coupling, and arousal/intensity.

## 2. Root cause

The Character Card expression materialization language was still too gentle:

```text
medium-arousal naturally amused laugh keyframe
```

Together with strict front-card framing, this pulled the renderer toward a
safe, pretty, centered portrait with parted lips. That is visually usable, but
it is not enough for the Professional Character Card default positive
expression slot. The product goal for `expression.laugh` is a static keyframe
that remains useful for future video/emotion control, not a near-neutral
commercial smile.

## 3. Correct contract

The generation contract must clarify that `expression.laugh` means:

- a clearly readable joyful laugh keyframe;
- not merely a polite open-mouth smile;
- medium-to-medium-high expression energy;
- engaged, lively gaze as expression evidence only;
- visible lower-lid/periocular participation;
- upper-cheek lift;
- relaxed jaw opening;
- natural age-appropriate teeth visibility;
- slight spontaneous asymmetry;
- a captured laugh phase from onset toward peak.

At the same time, the expression slot must keep the approved `face.front`
visual skeleton:

- vertical 2:3 reference-card frame;
- same camera distance, head size, top margin, eye-line, and shoulder span;
- same background treatment, lighting direction, white balance, complexion,
  wardrobe/style channel, visual finish, and material texture;
- no new scene, no full-body/half-body crop, no big-head close-up.

## 4. Scope and governance

This is a materialization-strength correction, not a review relaxation:

- shared expression score floors and issue codes remain unchanged;
- candidate budget remains 3 candidates plus at most one bounded repair;
- Provider and MCP still consume the same canonical prompt/reference package;
- no private Character Card reviewer or scoring path is added;
- no child-specific branch, cold-white skin recipe, or current-case style token
  is introduced;
- General, E-Commerce, Photography, ordinary Face Identity, and Body Silhouette
  are unchanged.

## 5. Validation

Focused tests must prove:

- Host default `expression.laugh` intent uses the stronger keyframe language;
- slot-delta Brain-timeout recovery emits the same stronger laugh contract;
- explicit optional `expression.smile` remains lower-intensity and does not
  inherit laugh keyframe language;
- shared Vision gates from Doc199 remain active and are not weakened.
