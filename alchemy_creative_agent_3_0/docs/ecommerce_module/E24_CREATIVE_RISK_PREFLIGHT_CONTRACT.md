# E24 Creative Risk Preflight Contract

Status: design proposal for reviewer audit; documentation only; no runtime
code, provider route, Brain schema, storage, slot, receipt, activation, or UI
behavior is changed by this document.

Owner: E-Commerce specialized module, with Professional Mode and shared Human
Realism as bounded contributors.

## 1. Why This Document Exists

The recent Professional E-Commerce product-on-model run showed that a
technically valid plan can still require many visual iterations when the first
plan does not explicitly reason about likely composition, reference, identity,
expression, and product-truth failure modes.

The observed repeated problems were not one narrow beachwear recipe:

- a back/look-back view can inherit a frontal identity reference too strongly,
  producing a pasted-face impression;
- a strong composition reference can accidentally donate its generic face;
- a dynamic or emotional image can ask for both action and a perfectly clear
  identity face, making the head and body feel assembled from different
  images;
- an open-mouth laugh can become a template advertising expression unless the
  affect is tied to body action and scene interaction;
- multiple product truth images are a factual pool, not a provider-facing
  requirement to use every image in every output;
- a close emotional hero can be valid even when it is not the image that proves
  full garment structure, as long as the set contains other structural views.

These are pre-generation planning risks. They should be reasoned about before
the Remote Brain signs the output set, rather than discovered only after pixels
are generated.

This document proposes a thin `creative_risk_preflight` contract. It is not a
new image recipe module and it does not replace existing E-Commerce,
Professional Mode, Human Realism, Product Truth, or Remote Brain authorities.

## 2. Current Capabilities Already Present

The current E-Commerce stack already has several relevant capabilities. New
work must reuse them instead of duplicating them.

### 2.1 Product truth and factual E-Commerce context

`EcommerceScenarioPackPlanner.build_creative_context()` already builds factual
`EcommerceCreativeContext`.

It owns:

- `product_truth`;
- marketplace/platform constraints;
- category evidence questions;
- seller-provided business facts;
- optional `apparel_on_model_evidence_profile`;
- `product_set_style` and `role_specific_creative_intent` when supplied by
  the server-shaped request context.

It explicitly does not own:

- shot order;
- camera and crop recipes;
- scene or pose recipes;
- final renderer prompts.

This boundary remains authoritative.

### 2.2 Remote Brain owns the E-Commerce output set

E17 and current runtime behavior make the Remote Brain responsible for:

- one whole-image natural-language direction per requested output;
- exact requested output count;
- output-set semantic variation;
- final canonical provider prompts through the finalizer stage.

Local E-Commerce code may validate and freeze returned structure, but must not
replace the Brain's creative answer with a local deterministic suite map.

### 2.3 Product truth pool and per-output admission

Recent Professional E-Commerce work established:

- uploaded product truth images form a complete auditable pool;
- each output admits only the product truth source or sources selected in the
  frozen `image_set_plan.evidence_dimensions_by_output`;
- selected product truth IDs must be non-empty, known, unique, role-valid, and
  within provider reference budget;
- unselected pool members must not leak into provider-facing
  `reference_assets`, `uploaded_assets`, or `reference_image_paths`;
- exceeding capacity fails closed rather than trimming, replacing, or silently
  using fewer facts.

The proposed risk preflight must not reselect product truth. It may only
describe risks and strategy hints that help the Brain choose well.

### 2.4 Apparel-on-model evidence profile

`ApparelOnModelEvidenceProfile` already supplies reviewable evidence dimensions
such as product view, movement, construction proof, context, camera crop, and
expression/pose.

It is deliberately not a shot recipe, scene recipe, or fixed output order.
Creative risk preflight may annotate risks around those evidence dimensions,
but must not invent a competing role taxonomy.

### 2.5 Professional Mode identity binding

Professional Mode already owns:

- selected People Asset;
- active Face Identity module / pack;
- immutable root provenance when required;
- approved identity view selectors such as front and profile;
- server-owned reference admission and binding snapshots.

For Professional requests, risk preflight may say that a look-back or side
view should prefer an approved profile identity view over a frontal identity
proof. It must not read raw output paths, forge bindings, replace the
Professional resolver, or downgrade to Standard Mode.

### 2.6 Human Realism and expression authenticity

Shared Human Realism and Expression Authenticity already own cross-template
human quality concerns:

- anti-plastic / anti-doll rendering;
- situation-owned expression;
- avoiding generic presenter smiles;
- head, face, body, hands, skin, and photographic material realism.

E-Commerce risk preflight must not duplicate these as a narrow shared rule. It
should provide context such as "this is an action-triggered laugh" or "this is
a back structure view where full frontal identity is not the primary proof",
then allow Human Realism and the Remote Brain to apply their own existing
authorities.

## 3. What Is Missing

The missing capability is not another static E-Commerce template. The missing
capability is a pre-generation risk analysis that turns current request,
reference roles, product truth, requested outputs, and active mode into
structured planning warnings.

The current system can say:

```text
Output 3 is a walking/look-back view.
Use product truth A.
Use identity references root + front/profile.
```

It does not yet consistently say:

```text
This output is at high risk of pasted-face artefacts if the face is too
frontal. Prefer a profile identity view, reduce head turn, and treat identity
as a side/back hint rather than a frontal proof.
```

The proposed preflight fills that gap.

## 4. Proposed Thin Contract

Add a structured `creative_risk_preflight` object to the E-Commerce planning
context after factual context and Professional binding have been resolved, but
before the Remote Brain authors the image set.

Example shape:

```json
{
  "contract_version": "ecommerce_creative_risk_preflight_v1",
  "owner": "ecommerce_specialized_preflight",
  "applies_to": "ecommerce",
  "mode": "standard|professional",
  "risk_items_by_output": [
    {
      "output_index": 1,
      "risk_family": [
        "template_expression",
        "pasted_face",
        "product_visibility_tradeoff"
      ],
      "primary_goal_hint": "emotion_hero",
      "strategy_hints": [
        "tie expression to visible action",
        "avoid static front-facing presenter grin",
        "preserve enough front product truth for hero readability"
      ],
      "authority_notes": [
        "Remote Brain chooses the final scene and prompt",
        "Product truth selection remains frozen through image_set_plan"
      ]
    },
    {
      "output_index": 3,
      "risk_family": [
        "over_twisted_head",
        "identity_angle_mismatch",
        "back_structure_occlusion"
      ],
      "primary_goal_hint": "back_or_lookback_structure",
      "strategy_hints": [
        "prefer profile identity evidence when Professional Mode provides it",
        "do not require full frontal facial clarity",
        "keep head neck shoulders and torso physically coherent"
      ],
      "authority_notes": [
        "Professional resolver owns identity view admission",
        "Remote Brain chooses the final natural action"
      ]
    }
  ],
  "global_risks": [
    "unselected_reference_role_leak",
    "composition_reference_identity_contamination"
  ]
}
```

This object must be concise, structured, public-safe, and free of local paths,
output file names, private job IDs, handoff IDs, provider payloads, and prompt
fragments.

## 5. Boundary: What The Preflight May And May Not Do

### 5.1 May do

The preflight may:

- classify uploaded/reference roles at a high level: identity, product truth,
  composition reference, emotional reference, scene reference;
- identify conflicts between roles, such as a composition reference whose face
  must not become identity truth;
- identify per-output risk families;
- propose strategy hints for the Brain and finalizer;
- surface Professional-only identity-angle hints when Professional Mode is
  active and approved view selectors exist;
- record that one output's primary goal is emotion, another's is structure,
  and another's is detail, without freezing a local scene recipe;
- carry stop/fail-closed hints when a risk cannot be represented safely.

### 5.2 Must not do

The preflight must not:

- choose final output roles independently of the Remote Brain;
- choose `selected_product_truth_asset_ids`;
- silently trim product truth;
- alter provider reference budgets;
- replace the Professional binding resolver;
- convert uploaded images into People Assets;
- add a local creative fallback;
- write final provider prompts;
- store or expose raw paths, internal IDs, job/handoff/output records, or
  provider payloads;
- put kidswear, beach, swimwear, or any other scenario recipe into General
  Template or shared Human Realism;
- make Standard Mode depend on Professional Mode assets.

## 6. Existing Versus New Responsibility Map

| Concern | Current owner | Proposed change | Interference guard |
| --- | --- | --- | --- |
| Product facts | ProductTruthLock / E-Commerce context | No ownership change | Preflight reads summaries only |
| Product truth pool | Native planner + Brain structured selection | No ownership change | Preflight cannot emit selected IDs |
| Output count | Remote Brain + runtime exact-count validation | No ownership change | Preflight cannot change N |
| Output creative direction | Remote Brain | No ownership change | Preflight supplies risks, not prompts |
| Apparel evidence dimensions | E-Commerce apparel profile + Brain mapping | Add risk annotations around them | No new role taxonomy |
| Identity binding | Professional Mode resolver | Add angle-risk hints only when active | No raw paths, no fallback |
| Human realism / expression | Shared Human Realism | Add situation context for risk | No narrow shared rule |
| Provider admission | Provider/materializer contracts | No ownership change | Preflight cannot change cap |
| Standard Mode | Existing Standard pipeline | May receive non-Professional E-Commerce risks | No People Asset lookup/injection |

## 7. Integration Model

### 7.1 Standard E-Commerce

Standard E-Commerce can use:

- product truth/reference role risks;
- composition-reference contamination risks;
- expression/action risks;
- product visibility versus emotion/scene tradeoff risks.

These hints are limited to commerce situation and product-composition tradeoff
context. Standard E-Commerce must not receive Professional identity-angle
strategy, People Asset-derived hints, or identity view availability.

It must not receive:

- People Asset binding data;
- face.front / face.profile references;
- Professional identity-angle strategy unless the request explicitly supplies
  non-Professional reference roles under Doc93 ownership.

### 7.2 Professional E-Commerce

Professional E-Commerce can additionally use:

- active identity view availability;
- front/profile/back-view identity-angle risks;
- advice that a back/look-back output should use profile identity evidence and
  avoid frontal proof pressure;
- warnings when a dynamic action asks for an unrealistically clear identity
  face.

The Professional resolver remains the only source of identity view admission.

### 7.3 Other templates

General Template must not load E-Commerce risk roles, product truth selection,
or commerce deliverable strategy.

Photography may later define its own preflight risk policy for session/role
risks, but it must not import E-Commerce product-on-model rules.

## 8. Learned Risk Families From The Controlled Run

The following are generic enough to become E-Commerce concepts. They become
shared only through existing Human Realism boundaries or through separately
proven foundation work; they are not beachwear-only recipes and must not be
promoted into shared Visual Capability merely because this controlled run found
them useful.

### 8.1 Reference-role contamination

When a generated or uploaded image is used as a composition reference, the
system must preserve its composition, pose, camera, or mood only if those are
declared as reference-owned. Its face, identity, product, hair, clothing, and
scene must not be inherited accidentally.

### 8.2 Identity angle mismatch

A side, profile, back, or look-back output should not be forced to prove
identity through a frontal face. If Professional Mode provides side/profile
views, those should be preferred for side/profile identity geometry. If no
profile identity exists, the Brain should reduce face size and turn angle
rather than invent a frontal proof on a back-facing body.

### 8.3 Pasted-face and over-twisted-head risk

When the body faces away but the face looks strongly back toward the camera,
the risk of a pasted-face impression increases. The strategy is to reduce head
turn, make the face secondary, rotate shoulders and neck coherently, and avoid
asking for a perfectly clear frontal face unless the output's primary goal is
identity proof.

### 8.4 Dynamic action versus identity clarity

Running, splashing, jumping, and turning are high-action moments. Asking for a
large, perfectly clear, highly consistent frontal identity face in those
moments can make the body and head feel assembled. Prefer smaller or angled
faces, scene-triggered expressions, and body-led motion.

### 8.5 Expression template risk

An explicit emotional goal such as joyful, playful, or happy is not a request
for a fixed mouth/eye geometry. The expression should emerge from the visible
action and attention. For active lifestyle hero images, the Brain should bind
laughter to hands, shoulders, torso, water/sand/object interaction, gaze, and
scene rather than a static front-facing smile.

### 8.6 Product evidence role tradeoff

An emotion hero does not need to prove every product angle. A back-structure
view does not need to be the strongest identity proof. A detail view can be
closer and less full-body. The output set must cover the total product truth;
each output should have a primary purpose and avoid carrying every purpose at
once.

### 8.7 Clean commercial polish risk

Photorealistic commercial outputs can still look AI-like when skin, smile,
water, hair, and pose are too symmetrical or too polished. Shared Human
Realism owns the generic material remedy; E-Commerce may tell the Brain which
moment should be candid, action-triggered, or product-proof rather than a
presentational display.

## 9. Superseded Or Narrowed Wording

The following older interpretations must be treated as narrowed for future
E-Commerce implementation work:

1. "Every uploaded product image must be admitted to every output."
   Superseded by the product truth pool model: full pool is audited, each
   output admits selected source or sources only.

2. "E-Commerce can rely on abstract apparel evidence dimensions alone."
   Narrowed: evidence dimensions remain valid but do not cover composition
   reference contamination, identity angle mismatch, expression template risk,
   or dynamic action versus identity clarity.

3. "Human Realism alone can solve product-on-model expression and pasted-face
   risks."
   Narrowed: Human Realism owns shared quality, but E-Commerce/Professional
   preflight should provide the per-output situation and reference-risk
   context.

4. "Professional identity references should always maximize face clarity."
   Narrowed: identity clarity must be compatible with output purpose and body
   geometry. Side/back/look-back outputs may intentionally use smaller,
   profile-informed, or secondary faces.

5. "A high-impact emotional hero must be a clear front-facing laugh."
   Narrowed: strong emotion should be action-triggered and body-integrated.
   Static frontal display laughter is only one possible solution and may be
   higher risk.

## 10. Implementation Plan

### Phase 1 — Documentation and test-only contract design

- Add this document and index it.
- Add no runtime behavior.
- Confirm Standard/Professional isolation requirements before implementation.

### Phase 2 — Data contract and deterministic tests

Add a typed `creative_risk_preflight` model under E-Commerce or scenario
runtime contracts, not under shared Visual Capability.

Focused tests must prove:

- General requests do not receive E-Commerce risk fields;
- Standard E-Commerce can receive non-Professional product/composition risks;
- Professional E-Commerce can receive identity-angle risk hints only when
  Professional Mode is selected and a binding exists;
- no product truth selection is emitted by preflight;
- no internal IDs/paths/provider fields leak;
- product truth pool selection remains owned by the existing Brain field;
- existing E-Commerce tests still pass.

### Phase 3 — Brain payload integration

Pass the concise preflight object through existing E-Commerce creative context
allowlists.

Tests must prove:

- the object reaches both semantic planning and finalizer only for E-Commerce;
- General and Photography payloads remain unchanged;
- Remote Brain still owns shot plan and final canonical prompts;
- finalizer receives risks as context, not as renderer prompt fragments.

### Phase 4 — Professional contributor

Add a Professional-only contributor that can emit identity-angle risk hints
after server-owned binding resolution.

Tests must prove:

- no People Asset lookup in Standard Mode;
- no Professional risk fields when Professional Mode is not selected;
- face.profile hints appear only when that view is available and approved;
- missing binding fails closed exactly as today.

### Phase 5 — Acceptance and rollout

Before any production enablement:

- run focused E-Commerce, General, Professional, Brain adapter, and provider
  materializer tests;
- run at least one zero-write planning-only validation for Standard
  E-Commerce and one for Professional E-Commerce;
- verify exact-N, product truth pool, identity binding, no-leakage, and prompt
  hash stability;
- do not claim improved final-pixel quality until real artifacts pass review.

## 11. Stop Conditions

Stop implementation and return to theory-first review if any of these occur:

- the preflight starts choosing product truth IDs;
- General requests receive E-Commerce role strategy;
- Standard Mode attempts to read People Asset metadata;
- Remote Brain output count or selected product truth contract changes without
  explicit tests;
- provider prompts contain internal risk codes, asset IDs, paths, or
  diagnostic wording;
- the new field becomes a local creative fallback after a Brain failure.

## 12. Reviewer Questions

1. Should `creative_risk_preflight` live in `EcommerceCreativeContext` or in a
   sibling runtime planning envelope that E-Commerce contributes to?
2. Should Professional identity-angle risk hints be carried inside the same
   object or as a nested `professional_identity_risk` section?
3. Which existing document should be marked as the current authority for
   product truth pool selection after this design lands: E24 alone, Doc259, or
   a follow-up implementation record?
4. Should Standard E-Commerce receive expression-template risk hints, or should
   those stay entirely in shared Human Realism with only an E-Commerce
   situation label?
5. What is the minimum browser/web workflow proof before exposing this in the
   user-facing Professional E-Commerce template?
