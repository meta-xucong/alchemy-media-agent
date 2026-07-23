# Doc204 — Character Card Laugh Eye-Cheek Coupling Calibration

Date: 2026-07-24

## Status

Implemented as a narrowly scoped shared affective-expression calibration.

Doc204 supersedes the weaker Doc200/Doc201 materialization wording where it
described laugh evidence as only “visible lower-lid/periocular participation”
or “upper-cheek lift”. Those remain useful review dimensions, but the renderer
contract must describe the coupled event more explicitly.

## Real validation evidence

Fresh MCP Character Card `expression.laugh` retry round on the six-year-old
reference-card asset proved the MCP/Provider handoff chain now works:

- explicit MCP handoff reaches stage-job creation, ScenarioRuntime generation
  metadata, Provider request construction, and MCP consumption;
- `mcp_handoff_d11761731d` consumed successfully into
  `v3_output_e5325f8dcaf24aacaad8`;
- `mcp_handoff_2c915da809` consumed successfully into
  `v3_output_dd810eece28848da8b45`;
- both outputs preserved identity, white-card framing, commercial cleanliness,
  and the Provider/MCP shared route.

The round still failed with `character_card_shared_review_failed`: the images
read as attractive open-mouth smiles or light laughs, but the eye/cheek/lower
face event was not strong enough to qualify as the professional default laugh
keyframe.

## Root cause

The structured contract had the right ownership, but the materializer projection
was too underspecified. “Visible lower-lid/periocular participation” still lets
the renderer produce a mouth-led smile: the mouth opens and teeth show, while
the eyes remain comparatively static and the cheeks do not clearly push into
the lower eyelids.

This is not a Provider outage, Brain timeout, policy refusal, or MCP parity
problem. It is expression materialization strength.

## Updated shared contract

`expression.laugh` remains a shared V3 foundation affective-expression
capability. Character Card owns the deliverable slot; it must not duplicate
private scoring, prompt recipes, review gates, Provider paths, or MCP paths.

The default positive Character Card slot now uses
`v3_affective_laugh_intent_v3` and adds `visible_eye_cheek_coupling`.

Renderer projection must require:

- a clearly readable joyful laugh keyframe, not a polite open-mouth smile;
- medium-to-medium-high expression energy;
- engaged gaze as expression evidence only, not lighting/style direction;
- clearly visible eye-cheek coupling where upper cheeks lift into lower eyelids;
- eyes remain open but become slightly narrower joyful crescent arcs;
- relaxed jaw opening and natural age-appropriate teeth visibility;
- mouth opening synchronized with cheek lift and periocular affect;
- slight spontaneous asymmetry;
- inherited face.front framing, style channels, lighting, complexion, wardrobe,
  background, and commercial finish.

## Non-goals

- Do not lower shared Vision floors to pass weak mouth-only smiles.
- Do not add child-specific branches. Child identity is only an age-conditioned
  fixture for the shared expression contract.
- Do not push bright/cool/fair skin, white background, or commercial finish as a
  global expression rule. Those channels are inherited from the approved
  `face.front` card or current prompt.
- Do not increase the candidate budget beyond three plus the already documented
  user-confirmed retry-round seam.

## Acceptance

- Provider and MCP use the same canonical expression materialization directive.
- Remote Brain response contract receives the v3 laugh intent and
  `visible_eye_cheek_coupling` participation channel.
- Regression tests prove the updated directive reaches recovered Character Card
  `expression.laugh` prompts without leaking into ordinary non-expression
  prompts.
- Fresh MCP validation starts a new confirmed failed-slot retry round; old
  failed candidates remain append-only history and cannot be promoted.
