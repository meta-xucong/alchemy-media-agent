# Doc168 — Remote Brain Reference-Channel Ownership Execution Closure

Status: implemented and verified as the shared reference-ownership authority.

Related authority: Doc76, Doc91–96, Doc140, Doc148, Doc159, Doc161, Doc166 and Doc167.

## 1. Demonstrated defect

The post-Doc167 benchmark run proved that developmental-age and Human Realism
contracts reached the final Brain, but an ordinary portrait identity source was
still materialized as both a derived identity crop and the complete original
frame. The complete source frame carried older-stage head geometry, warm garden
color, source camera and source scene evidence into a new approximately-six-year
commercial portrait.

The cause was not insufficient child-specific prompting. The active Doc93
reference policy still rediscovered prompt ownership with a local keyword table,
clause splitting and preserve/change term proximity. In a request that meant
“same person, new head-and-shoulders camera”, the word “same” was incorrectly
associated with the camera clause and froze `camera_composition` as a source
channel. The later Doc161 Brain sign-off could only approve or rewrite a prompt
against that already-wrong frozen policy; it could not remove the extra source
frame.

This is an architecture defect. Adding more complexion, cheek, gaze or child
keywords would conceal rather than fix it.

## 2. Required forward path

For every new enforced real-image request, reference-channel ownership must be:

```text
user meaning + declared reference roles
→ Remote Brain semantic VisualTaskProfile
→ typed ReferenceChannelOwnershipIntent
→ shared Doc93 role defaults and conflict resolution
→ frozen reference policy / envelope / ledger
→ canonical Brain finalizer sign-off
→ one canonical prompt and the admitted reference pixels
```

The Remote Brain decides which channels the current request explicitly assigns
to a reference and which channels the current request owns. The shared runtime
may validate channel names, disjointness, evidence shape and applicability. It
must not infer semantic ownership from words, regular expressions, phrase
distance, demographic labels or scene-specific examples.

## 3. Typed semantic contract

`VisualTaskProfile` gains one compact semantic object:

```text
ReferenceChannelOwnershipIntent
  applicability: applicable | not_applicable | ambiguous
  decision_owner: remote_brain | evidence_fallback | legacy
  reference_owned_channels: valid shared channel IDs[]
  current_request_owned_channels: valid shared channel IDs[]
  evidence_ids: VisualTaskProfile evidence IDs[]
  confidence: 0..1
```

This is an ownership ledger, not renderer prose. It must never contain a
prompt fragment, negative prompt, facial recipe, child/kidswear branch, camera
recipe or provider instruction.

For an enforced job with admitted references:

- the intent must be `applicable` and owned by `remote_brain`;
- the two ownership lists must be valid and disjoint;
- ambiguity, absence or a non-remote owner blocks before Provider;
- “same person” does not by itself assign hair, wardrobe, complexion, camera,
  scene, lighting, expression or whole-image style to the source;
- a new crop, camera, scene, light, wardrobe, expression or commercial
  complexion requested by the user remains current-request-owned unless the
  user semantically assigns that channel to the reference;
- generic role truth remains shared and universal: an ordinary portrait source
  supplies identity geometry by default, a product source supplies product
  identity, and a style/scene/composition source supplies only its declared
  role.

## 4. Compatibility boundary

Historical jobs may continue to read the old deterministic ownership record.
That resolver is non-certifying compatibility only. It must not execute for a
new enforced request and must not influence Provider references, canonical
prompt materialization, review, retry or delivery.

Doc161 remains valid as the final complete-prompt Brain sign-off. Doc168 moves
the semantic ownership decision early enough to govern which pixels are
admitted before Doc161 signs the final prompt.

## 5. Human Realism benchmark consequence

The external child-model boards remain human evaluation references only. They
must never be sent to Provider or stored as identity evidence. The only
Provider identity reference remains the user-authorized source asset.

After this correction, the controlled approximately-six-year comparison must
be repeated with:

- source identity preserved without inheriting source age, camera, scene,
  lighting, wardrobe or whole-frame finish;
- current commercial complexion intent preserved without yellow/orange source
  color contamination;
- camera-observed skin material, natural fine color variation and restrained
  highlights;
- stage-coherent soft-tissue fullness, gaze, affect and lower-face proportions;
- neutral and lively expressions judged independently.

No local cheek, eye, mouth, tooth, collagen, skin-color or age prompt recipe is
permitted. Those qualities remain holistic Brain-owned rendering decisions and
shared Vision/human-review criteria.

## 6. Red regressions

The implementation must prove:

1. the compact remote schema requires the typed ownership intent;
2. an enforced reference-conditioned job fails closed when the intent is
   absent, ambiguous or not remotely owned;
3. “same person” plus a new crop/scene/light does not lock source camera or
   whole-frame style;
4. an explicitly source-owned outfit or scene remains possible when the Brain
   assigns it;
5. identity-only developmental transition suppresses the complete source frame
   and keeps only the admitted identity derivative;
6. same-stage Doc95, Professional 2/3/5 reference budgets, product identity,
   non-human identity and no-reference jobs retain their existing contracts;
7. new enforced execution cannot call the local keyword/proximity resolver;
8. canonical Web and Local MCP prompts and reference hashes remain identical.

## 7. Acceptance and stop condition

Code acceptance requires focused and full regressions, compile checks, plugin
validation, diff audit and no temporary evidence files. Visual acceptance then
requires a fresh canonical Local MCP run using the exact Brain-signed prompt and
admitted reference path. Shared Vision may certify the pixels, but the stricter
human benchmark comparison is decisive for complexion, skin material,
soft-tissue fullness, gaze, affect and lower-face developmental coherence.

If the output remains below the benchmark, the next iteration must start from
new evidence attribution. It must not reintroduce local semantic parsing or a
child-specific prompt stack.

## 8. Implementation result

Fresh enforced reference-conditioned execution now requires the Remote Brain's
typed, canonical channel ownership intent. Missing, ambiguous, aliased or
non-remote decisions fail closed before reference materialization. The prior
keyword/proximity resolver remains readable only through an explicitly
non-certifying compatibility method and cannot govern a new real-image job.

The controlled transition run proved that the complete source frame was
suppressed and that only one provider-only identity derivative remained. The
canonical Web/Local materializer prompt and reference contract stayed aligned.
That run also exposed the narrower Doc169 evidence-contour issue; it did not
invalidate this ownership correction.
