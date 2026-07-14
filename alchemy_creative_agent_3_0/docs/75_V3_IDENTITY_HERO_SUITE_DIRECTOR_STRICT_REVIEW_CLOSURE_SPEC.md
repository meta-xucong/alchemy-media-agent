# 75 V3 Identity Hero, Suite Director, And Strict Review Closure

> Historical/compatibility notice (Docs93, 95, 111, and 113): identity evidence
> and append-only best-result observations remain useful, but the shared hero
> selector, suite director, role recipes, and negative-prompt proposals below
> are not forward runtime authority. Do not bring them into General, E-Commerce,
> Photography, Brain requests, or Provider prompts for new jobs.

Doc94/95 correction note:

```text
Doc75 is historical source material for identity and review observations. Its
named portrait cases and negative terms are fixtures, not shared runtime
profiles. Doc94 owns universal visual variables; Doc95 owns complete identity
evidence and per-role best-result selection after retry.
```

## 1. Purpose

This document is not current authority for a new General Template quality pass.
Use Docs93, 95, 111, and 113 for forward work.

The goal is not to add another large framework. The goal is to close the gap
between three existing abilities:

```text
identity continuity
purposeful multi-image suite roles
real generated-output review and bounded retry
```

The new closure must make V3 behave like a commercial creative system:

```text
1. Pick or establish one strong identity master.
2. Direct the rest of the image set around clear visual duties.
3. Strictly review the generated results and retry only when a fixable issue is found.
```

## 2. Compatibility

Doc75 extends the existing V3-native Visual Capability Cluster.

It does not replace:

```text
Project Mode
ScenarioRuntime
Scenario Packs
Product API
Generation provider layer
CentralCreativeBrain
LLM Brain adapter
Doc53 retry guardrails
Doc54/59 four General Template modes
Doc65 Human Photorealism layer
Doc73 first-output identity anchor
Doc74 complex prompt and negative-prompt splitting
```

The implementation must stay under:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/
```

The CentralCreativeBrain and fallback Brain may only consume the cluster output.
They must not instantiate or rebuild Doc75 child logic.

## 3. Module Ownership

Doc75 adds two child responsibilities inside the Visual Capability Cluster:

```text
identity_hero_selector
strict_visual_review_policy
```

These are submodules of the existing visual cluster. They are not independent
runtime frameworks.

### 3.1 identity_hero_selector

This child module decides how the first reliable identity direction is chosen.

Priority order:

```text
1. User-selected output or uploaded identity reference.
2. Existing project identity anchor.
3. Strong reference binding from the project context.
4. First generated human portrait in a text-only multi-image job.
```

Rules:

```text
manual user references always win
auto first-output anchor is only a fallback
identity master must show a readable real face
identity master must have natural head, neck, shoulder, and body proportion
identity master must be attractive enough to guide the set
later outputs must keep the person while varying role-specific expression, pose, camera, crop, or scene depth
```

### 3.2 strict_visual_review_policy

This child module defines stricter pass and retry criteria.

It must inspect or consume generated-output review signals and classify
retryable issues such as:

```text
identity drift
hair or outfit drift
role collapse
same expression/head angle/pose repetition
bad hands or distorted body
generic AI beauty identity
plastic or over-smoothed skin
suppressed fair complexion when not requested
gray or forced tan cast when not requested
head/body proportion distortion
visible watermark, AI mark, random text, or label artifact
low commercial finish
```

Retry must remain bounded by Doc53.

## 4. Suite Director Closure

Doc75 does not replace Doc54/59 modes.

The four modes remain:

```text
similar_candidates
delivery_suite
creative_exploration
format_adaptation
```

Doc75 strengthens how each mode closes:

```text
similar_candidates:
  generate alternatives around the same identity and same brief, with controlled pose/expression/style differences

delivery_suite:
  produce visually different roles such as cover hero, closer detail, side or three-quarter portrait, wider lifestyle/environment frame

creative_exploration:
  explore larger visual directions without losing the central subject identity

format_adaptation:
  adapt the same direction to aspect ratios and composition lanes without changing the subject identity
```

The output set is not accepted just because images exist. It is accepted only
when the role plan, identity continuity, and commercial finish are all usable.

## 5. Anti-AI Feel And Negative Prompt Absorption

Doc75 absorbs useful negative constraints from the previous detailed portrait
prompt. These terms must be treated as avoid rules, not desired content:

```text
Korean glass skin
oily shiny face
nose-tip highlight
silicone face
over-smoothed skin
heavy makeup
plastic texture
distorted fingers
wrong dress structure
distorted human proportions
strong HDR
over-sharpening
anime
illustration
CG
3D render
```

For East Asian fresh, summer, seaside, beauty, or social-cover portrait
requests, the default should be:

```text
clean fair luminous complexion through real light and color balance
natural skin texture
attractive real-camera expression
no forced tan, bronze cast, gray-brown cast, wax skin, or beauty-app geometry
```

The system must not overcorrect into dark, tired, or unflattering realism unless
the user asks for that exact look.

## 6. Prompt And Provider Consumption

The provider prompt must receive Doc75 guidance from metadata, not by duplicating
logic in the provider.

The provider prompt should include:

```text
suite director rules
identity hero selection rules
strict visual pass conditions
role-specific keep and avoid rules
negative constraints from Doc74 and Doc75
```

The LLM Brain fallback may summarize these rules in checkpoints, but it must
not own the rules.

## 7. Review And Retry

Doc75 retry behavior:

```text
retry only if a retryable issue code is detected
retry only for the affected generated candidate or job pass
merge retry prompt additions and negative additions from visual review
do not retry for provider outage, balance, policy block, or unrelated infrastructure failure
do not retry forever
do not keep retrying when the same issue repeats at the retry limit
```

The retryable issue whitelist must include Doc75 human and suite quality issue
codes so real review signals can trigger the existing Product API retry path.

## 8. Beginner-Facing UX

Doc75 is mostly backend quality logic.

The UI should not expose:

```text
identity_hero_selector
strict_visual_review_policy
candidate_id
retry patch
provider metadata
```

The UI may summarize the result in beginner language:

```text
locked a clear person direction
made this set follow the same person
gave each image a different use
filtered obvious AI marks and weak results
```

## 9. Implementation Steps

1. Add `IdentityHeroSelectionPlan` and `StrictVisualReviewPolicy` contracts.
2. Build both plans inside the existing Visual Capability Cluster.
3. Attach identity hero metadata to the primary role recipe.
4. Add strict review prompt additions, negative additions, pass conditions, and
   retryable issue codes to the role plan.
5. Make quality review reports consume strict issue codes from metadata and
   generated candidates.
6. Make commercial output selection prefer the identity hero role when it passes.
7. Make provider prompts consume suite, identity, and strict review rules from
   cluster metadata.
8. Extend Product API retry issue whitelist for Doc75 issue codes.
9. Add focused Doc75 tests.
10. Run real validation with the East Asian summer seaside portrait case.

## 10. Acceptance Tests

Focused tests must prove:

```text
visual cluster exposes identity_hero_selection_plan
visual cluster exposes strict_visual_review_policy
manual user references have priority over auto identity master selection
provider prompt contains identity hero and strict review guidance
strict review issue codes can produce an auto retry decision
Product API retry whitelist includes Doc75 AI-face, role-collapse, and proportion issue codes
Doc74 explicit negative-prompt splitting remains intact
Doc73 first-output identity anchoring remains intact
```

Real validation should generate the previous East Asian summer seaside portrait
set and compare:

```text
identity consistency
natural expression/action/camera variation
clean fair complexion without wax skin
no obvious AI marks or text
suite role differentiation
commercial photo finish
```

## 11. Current Authority

If Doc75 conflicts with earlier documents:

```text
Doc50 and Doc67 still win for module ownership boundaries.
Doc53 still wins for retry budget and loop safety.
Doc54/59 still win for the four mode definitions.
Doc73 still wins for first-output identity anchor mechanics.
Doc74 still wins for splitting explicit negative prompts.
Doc75 wins for identity master selection, suite-director closure, strict visual pass conditions, and Doc75 retryable quality issue codes.
```
