# 95 V3 Universal Portrait Identity Evidence And Best-Result Closure Spec

## 1. Purpose

Doc95 strengthens same-person identity after Doc94 removes scenario overfit.
It is a universal portrait-reference capability, not a historical-style or
General-Template-specific recipe.

The target is:

```text
keep the uploaded person's underlying identity
allow prompt-owned makeup, hair, wardrobe, light, scene, camera, and mood
avoid source-frame style leakage
keep the best inspected attempt instead of assuming the latest retry is better
```

## 2. Evidence From Historical Results

The accepted historical comparison is diagnostic evidence only:

```text
older high-identity output a661:
  one source image became three provider images
  wide face crop + appearance crop + full original
  stronger same-person readability
  source hair and old visual direction leaked

intermediate output 857:
  two identity crops
  cleaner prompt ownership
  identity remained stronger than the current single-crop path

current output fe313:
  one tight, almost grayscale identity crop
  strongest prompt-owned style cleanliness
  weaker jaw, cheek, brow, nose-mouth, and overall same-person continuity
```

The runtime must not know these output ids or their visual genre. They remain a
regression fixture demonstrating a general tradeoff between identity evidence
and source-style leakage.

## 3. Compatibility

Doc95 extends:

```text
Doc73  first-output identity anchor
Doc75  identity hero and strict review
Doc78  long-term identity
Doc85  image-to-image reference truth
Doc86  bone-structure identity lock
Doc87  identity/style separation
Doc88  prompt/reference balance
Doc90  user-facing reference priority
Doc93  reference-channel policy
Doc94  shared-runtime de-overfitting
```

Doc95 does not change Project Mode, ScenarioRuntime, Scenario Packs, provider
routing, the 15k semantic prompt target, or the existing Advanced UI.

## 4. Universal Identity Evidence Pyramid

An identity-only portrait source produces two complementary provider images:

### 4.1 Feature Detail Evidence

Must preserve:

```text
eyebrows and brow-eye relationship
eye shape, eye size family, and spacing
nose bridge, tip, wings, and nose-mouth relationship
mouth width, lip contour, philtrum, and lip fullness family
cheek transition and visible face outline
```

### 4.2 Head Geometry Evidence

Must preserve:

```text
full forehead and hairline boundary
temples and cheekbone direction
face width/length and three-part facial proportion
ears or side-face boundary when visible
jaw width, jawline slope, chin scale, and upper-neck relationship
```

The geometry evidence is wider than the feature evidence but still excludes
most wardrobe, environment, and old composition.

### 4.3 Evidence Processing

```text
use a reliable face region from metadata when available
otherwise use a conservative subject-safe fallback crop
never crop away the chin, jaw corners, forehead, or both temples
preserve moderate natural color after neutral white balance
do not reduce identity evidence to near-grayscale
retain enough natural color and tonal separation for brows, eyes, nose, lips,
and face-plane transitions to remain readable
do not synthesize a flat matte or artificial background
keep valid JPEG geometry for gateway compatibility
compress each derivative independently and bound their combined payload
do not duplicate identical bytes to simulate strength
```

Default transport budget:

```text
two portrait identity derivatives
each target at or below 480 KB when possible
combined identity evidence target at or below 960 KB
minimum short edge 512 px
```

The complete original remains in project history. It is sent upstream only
when Doc93 explicitly assigns source-owned hair, wardrobe, appearance, scene,
lighting, camera, mood, or style channels.

The provider prompt must explicitly state that both derivatives are
complementary crops of one single source person. Feature-detail evidence owns
the brow-eye and nose-mouth relationships; head-geometry evidence owns the
forehead, face ratio, temple-cheek-jaw contour, jaw slope, and chin scale. The
model must never interpret them as two candidate identities or average them
into a generic beauty face.

For reference-conditioned portrait jobs, the provider prompt begins with an
identity-preserving edit operation before scene and style direction. It states
that the task edits the exact supplied person rather than casting or generating
a similar model, and that same-person geometry outranks generic beauty,
premium, delicate, elegant, genre, or style vocabulary. This is a universal
operation contract, not a scene recipe.

## 5. Identity Source Priority

```text
1. user-uploaded portrait truth
2. user-confirmed generated identity reference
3. automatic selected-output continuation anchor
4. text-only temporary batch anchor
```

User-confirmed generated images may serve as an identity bridge only through
the existing reference-selection contract. They never replace uploaded truth.

Unselected generated results never become positive identity memory.

## 6. Protected Identity-Critical Prompt Block

The 15k provider materializer must reserve one concise, non-droppable block.

Required dimensions:

```text
face width/length ratio
forehead, midface, and lower-face proportion
temple, cheek volume, and cheekbone direction
jaw width, jawline slope, and chin scale
eyebrow base shape and brow-eye relationship
eye shape, size family, and spacing
nose bridge, tip, wings, and nose-mouth relationship
mouth scale, width, philtrum, lip contour, and fullness family
natural age and body-identity direction
```

Generic beauty terms may affect presentation, makeup, expression, lighting,
and styling. They may not replace these dimensions.

When portrait identity truth exists, attractiveness is identity-owned. The
system may improve presentation through prompt-owned makeup, expression,
camera, light, color, and realistic rendering, but it must not optimize,
harmonize, slim, sharpen, enlarge, or otherwise redesign the reference person's
base feature geometry in pursuit of a generic beauty target.

The block must remain concise and must not restore duplicated framework prose.

## 7. Identity Review Contract

Generated output and identity truth images must be inspected together.

The reviewer reports independent scores:

```text
face_outline_and_proportion
brow_eye_geometry
nose_mouth_relationship
jaw_chin_geometry
age_identity_direction
same_person_readability
prompt_owned_channel_obedience
human_realism
commercial_finish
```

The reviewer must ignore allowed makeup, hairstyle, wardrobe, expression,
pose, camera, and light changes when judging identity.

Retry output includes structured deltas instead of a generic "look more like
the reference" instruction:

```text
restore face width/length direction
restore eye spacing or base eye shape
restore nose-mouth scale relationship
restore jaw width, slope, or chin scale
remove beauty-template geometry replacement
```

## 8. Best-Result Closure

A retry is another candidate, not an automatic winner.

Selection hard gates:

```text
identity truth respected
prompt-owned channels respected
no fail-final artifact or policy issue
usable output file exists
```

Selection priority after hard gates:

```text
same-person readability       45%
prompt channel obedience      25%
human realism                 15%
commercial finish             15%
```

Behavior:

```text
if retry clearly improves the failing dimension without damaging hard gates,
deliver retry
if retry is worse, retain the earlier candidate as final delivery
if both fail differently, stop at the retry limit, keep both internally, and
deliver the higher-scoring usable result with an audit warning
never start an unbounded generation loop
```

Requested multi-image sets apply the same comparison per affected role. A
retry must not replace unrelated successful images.

## 9. Architecture Placement

No new top-level visual framework is allowed.

```text
visual_cluster/portrait_identity.py
  owns the universal identity dimensions, source priority, and review deltas

visual_cluster/reference_channel_policy.py
  owns channel inheritance rights

src_skeleton/app/services/provider_reference.py
  materializes the two provider-safe identity derivatives

generation_router/providers.py
  sends accepted evidence and protects the identity-critical prompt block

visual_cluster/vision_provider.py and vision_inspector.py
  compare generated output with reference truth and return structured scores

product_api/service.py
  performs bounded retry comparison and records the preferred final output

project_mode/service.py
  displays the preferred delivery result and folds non-winning attempts into
  project history
```

## 10. Frontend

No new beginner control is required.

Existing behavior remains:

```text
automatic mode chooses the policy
High person consistency activates the strict universal identity path
user-selected reference images have highest explicit priority
project result cards show only preferred delivery outputs
all attempts remain visible in folded project records
```

## 11. Development Steps

1. Finish and test Doc94 correction first.
2. Add a second portrait identity derivative and payload metadata.
3. Keep full identity originals suppressed under identity-only Doc93 policy.
4. Restore the full identity dimension set in the protected prompt block.
5. Add derivative count, type, byte size, color retention, and source id audit
   metadata.
6. Extend visual review with identity dimension scores and deltas.
7. Persist per-attempt review scores against output ids.
8. Select the best reviewed attempt without changing retry limits.
9. Keep non-winning attempts append-only and hidden from beginner result cards.
10. Run cross-scene and full regression tests before real generation.

## 12. Tests

### 12.1 Evidence Tests

```text
one identity-only upload produces exactly two non-identical derivatives
both derivatives preserve valid JPEG geometry and minimum size
combined payload remains bounded
full original is suppressed for identity-only policy
full original returns when an explicit source-owned style/scene channel exists
off-center fallback does not remove the full jaw and forehead
```

### 12.2 Prompt Tests

```text
all identity dimensions survive the 15k semantic materializer
the complete user prompt survives
no cultural, costume, age-market, or ethnicity recipe is injected
generic beauty words cannot replace identity geometry
```

### 12.3 Review And Delivery Tests

```text
retry pass beats initial fail
initial pass or stronger warning beats a worse retry
different retry failure does not erase the better initial result
requested output count remains exact
non-winning attempts remain in project history
no additional retry occurs after the configured limit
```

### 12.4 Cross-Scene Matrix

Use the same identity source across at least:

```text
bright modern portrait
low-key cinematic portrait
indoor commercial portrait
outdoor documentary portrait
different wardrobe and hairstyle
different camera distance and head angle
```

Historical period-style images may be one fixture, never the only fixture.

## 13. Acceptance Target

Doc96 extension: these targets must be measured with the fused objective and
multimodal identity gate when that capability is available. A subjective score
alone is insufficient for claiming stable 0.8+ identity. Doc96 governs high
input fidelity, ephemeral metrics, framework-prompt deduplication, and bounded
face-local repair; Doc95 continues to govern complementary evidence and
best-result delivery.

```text
average same-person score >= 83/100
minimum same-person score >= 78/100
prompt-owned channel score >= 88/100
no full-source scene/hair/light leak under identity-only policy
no generic beauty-template face replacement
no provider request-body regression
full V3, frontend/API, root, compile, and static audits pass
```
