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

### 4.1 Closure note: typed field contract before implementation

The example above is illustrative only. Before any runtime implementation, the
contract must be represented as a closed typed schema, not as free-form
strategy text. This closure note narrows the implementation target without
changing runtime behavior.

Required top-level fields:

| Field | Type | Allowed values / constraint | Owner |
| --- | --- | --- | --- |
| `contract_version` | enum | `ecommerce_creative_risk_preflight_v1` | E-Commerce specialized module |
| `owner` | enum | `ecommerce_specialized_preflight` | E-Commerce specialized module |
| `applies_to` | enum | `ecommerce` | E-Commerce specialized module |
| `mode` | enum | `standard`, `professional` | caller mode, validated by runtime |
| `risk_items_by_output` | array | empty only when no output-level risk is present; otherwise unique 1-based `output_index` values within requested N | E-Commerce preflight |
| `global_risks` | array of enum | subset of the closed `risk_family` enum; no additional values | E-Commerce preflight |

Required per-output fields:

| Field | Type | Allowed values / constraint |
| --- | --- | --- |
| `output_index` | integer | 1-based index within requested output count |
| `risk_family` | array of enum | see allowed `risk_family` values below |
| `primary_goal_hint` | enum | `emotion_hero`, `playful_interaction`, `walking_or_lookback`, `back_or_structure`, `product_detail`, `balanced_lifestyle_product`, `safe_static_product_proof` |
| `risk_level` | enum | `low`, `medium`, `high` |
| `strategy_policy` | array of enum | see allowed strategy values below |
| `stop` | boolean | true only when the risk cannot be represented safely |
| `fail_closed_reason` | enum or null | required closed enum when `stop=true`; null otherwise |
| `professional_identity_hint` | object or null | present only in Professional Mode and only after an approved binding/view set exists |

`risk_items_by_output` cardinality rules:

- It may be `[]` only when the preflight found no output-level risk that needs
  to be carried forward.
- When non-empty, each item must refer to a unique `output_index`.
- `output_index` is 1-based and must be within `1..requested_image_count`.
- Duplicate, zero, negative, non-integer, or greater-than-N output indexes are
  schema-invalid and must fail closed before any Remote Brain planning payload
  is accepted.
- Missing an output is allowed only when that output has no risk item; missing
  an output must not be interpreted as permission to drop that output from the
  exact-count set.

Allowed `risk_family` values:

- `composition_reference_identity_contamination`
- `unselected_reference_role_leak`
- `identity_angle_mismatch`
- `pasted_face`
- `over_twisted_head`
- `template_expression`
- `dynamic_action_identity_clarity_conflict`
- `product_visibility_tradeoff`
- `product_detail_context_loss`
- `back_structure_occlusion`
- `head_body_scale_mismatch`
- `stiff_catalogue_card_direction`
- `ai_polish_or_plasticity`

`global_risks` must use this same closed `risk_family` enum and may contain
only risks that apply to the whole request or set. Unknown values, free-text
phrases, duplicate entries, or values outside the `risk_family` enum are
invalid. `global_risks` must not introduce a second risk vocabulary.

Allowed `strategy_policy` values:

- `action_triggered_expression`
- `avoid_static_presenter_grin`
- `coherent_secondary_turn`
- `avoid_over_twisted_head`
- `prefer_body_led_motion`
- `keep_face_secondary_when_back_or_profile`
- `preserve_product_truth_readability`
- `separate_composition_reference_from_identity`
- `preserve_environment_integration`
- `use_detail_role_for_close_product_evidence`
- `fail_closed_if_reference_roles_conflict`

Allowed `fail_closed_reason` values:

- `unsafe_or_unrepresentable_reference_mix`
- `missing_required_professional_binding`
- `missing_approved_identity_view`
- `identity_strategy_unavailable`
- `reference_role_conflict`
- `product_truth_selection_contract_conflict`
- `provider_reference_capacity_unrepresentable`
- `exact_count_contract_conflict`
- `unknown_or_invalid_preflight_enum`
- `internal_field_leak_risk`

Unknown `fail_closed_reason` values are invalid and must be rejected rather
than logged as free text.

When any per-output item has `stop=true`, the whole N-output planning request
fails closed before Remote Brain planning or finalizer sign-off is accepted.
The system must not silently delete that output, reduce N, split the request
into smaller jobs, switch routes, fall back to local creative logic, patch the
prompt, or continue by ignoring the stopped output. Exact-count authority
remains stronger than preflight convenience.

The `professional_identity_hint` object is a Professional-only contributor. It
may contain only:

```json
{
  "preferred_identity_view_kind": "front|front_three_quarter|profile|back|none",
  "identity_strategy": "front_primary|profile_primary|secondary_face|identity_not_primary",
  "source": "professional_binding_resolver"
}
```

It must not contain raw asset IDs, paths, output IDs, handoff IDs, prompt text,
hashes, or provider payload fragments. It also must not select reference images.
The Professional resolver remains the only owner of identity view admission and
server-owned binding evidence. The preflight may describe the strategy implied
by already-resolved view kinds; it may not create, rank, or substitute views.

Head-turn and face/body coherence guidance must use finite strategy enums such
as `coherent_secondary_turn` and `avoid_over_twisted_head`. It must not be
written as a provider prompt fragment and must not hard-code numeric head angles
or pose degrees. The Remote Brain remains responsible for converting the typed
risk context into a natural shot direction and final canonical prompt.

### 4.2 Acceptance matrix

| Scenario | Expected preflight behavior |
| --- | --- |
| General Template | No `creative_risk_preflight` field and no E-Commerce risk-role fields. |
| Standard E-Commerce | May receive commerce situation, reference-role, expression/action, and product-composition risk context. Must not receive People Asset, identity view availability, or Professional identity-angle hints. |
| Professional E-Commerce with approved binding/views | May receive `professional_identity_hint` using only approved view kinds and strategy enums. No raw IDs, paths, hashes, or view selection. |
| Professional E-Commerce without approved binding/views | Must omit `professional_identity_hint`; if the requested risk cannot be represented safely, set `stop=true` with a closed `fail_closed_reason`. |
| Product truth selection | Unchanged. `selected_product_truth_asset_ids`, product pool, source hashes, provider cap, and omission lineage remain owned by the existing Remote Brain `image_set_plan` / native materialization contract. |
| Output count / exact N | Unchanged. Preflight cannot change requested output count or silently split a set. |
| Remote Brain prompt authority | Unchanged. Preflight supplies typed risk context only; Remote Brain still authors shot plan and canonical prompts. |
| Fallback / leakage | No local creative fallback, no prompt patching, no internal IDs/paths/provider fields in Brain-visible or provider-visible text. |

### 4.3 Post-review boundary

Post-generation pixel review remains a shared Human Realism / Review
responsibility. E-Commerce preflight may provide scenario risk context such as
"this output is a look-back structure shot with high pasted-face risk", but it
must not move pixel gates, identity metrics, head/body scoring, expression
authenticity scoring, hand/foot checks, or retry authority into the E-Commerce
specialized module. Any later review implementation must call the existing
shared review/foundation path and preserve its ownership.

### 4.4 Evidence boundary from Doc259 Section 13K

Doc259 Section 13K records the current `n6-dynschema` state: six
conversation-only host artifacts, six host receipts, preliminary visual pass,
and zero business mutation. That evidence is valid learning input for E24, but
it is not runtime authority. It did not create FormalSlotReceipt records,
project outputs, slots, activations, public projection, or a production delivery
contract. E24 must not treat those artifacts as proof that this preflight
contract is already implemented.

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
