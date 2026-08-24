# V3 Brain-First Human Realism Minimal Optimization Plan

## 1. Objective

Improve one-shot human realism for V3 visible-person images while preserving
the user's requested scene, mood, beauty, camera language, and reference
ownership.

The target is generation-time quality. Visual review remains an audit signal;
it does not automatically trigger a retry or attempt to repair an image.

This plan is a minimal implementation refinement of the existing shared Human
Realism capability. It is not a new scene template, provider, or image-quality
pipeline.

## 2. Authority

This plan extends, and does not replace:

- Doc91: shared Human Realism Plugin ownership.
- Doc92: style-aware AI-feel suppression.
- Doc94: universal visual capability and anti-overfitting governance.
- Doc138: Brain-owned natural presence.
- Doc150: human presence, materiality, and expression resolution.
- Doc170: aesthetic and camera-material conjunction.

The Brain is the only component that interprets the complete visual situation
and authors the final human-realism direction. Deterministic runtime code must
not infer facial parts, build keyword recipes, or append local repair prose.

## 3. Current Gap

The shared capability can activate and produce semantic contracts and review
receipts, but Brain-owned execution may still deliver a generic
photorealistic direction. A receipt proves that the contract was handled; it
does not prove that the final renderer direction resolved:

- natural skin and highlight response under the requested light;
- distinct individual presence in a multi-person image;
- situation-owned attention and expression;
- believable contact between hair, clothing, hands, objects, and scene;
- attractive realism without a uniform beauty-filter finish.

The observed result may therefore pass workflow checks while retaining visible
AI polish, smooth skin, repeated faces, and overly clean materials.

## 4. Minimal Correction Model

### 4.1 Brain-owned final direction

For every active visible-person generation, the final Brain response must
contain one complete, scene-aware human photographic direction. It must be
written as an integrated image decision, not as a list of facial or skin
attributes.

The direction must reconcile, when applicable:

- personhood and individual variation;
- camera-observed human material and natural complexion;
- attention, expression, pose, and interaction;
- physical light, depth, contact, and surface response;
- explicit user style and reference channel ownership.

The direction must remain appropriate to the requested mood. Human Realism may
reduce synthetic rendering, but may not force bright commercial light, alter
the user's aesthetic, or replace a requested attractive subject with a bland
one.

### 4.2 Renderer transport

The Brain-authored direction must be carried into the existing canonical
provider prompt through the current Brain/adapter transport. The Provider does
not interpret or rewrite it.

The existing semantic contract and safe receipt remain audit metadata. They are
not treated as a substitute for the final Brain-authored direction.

### 4.3 No automatic retry

Human-realism review findings remain available for diagnostics and user-facing
audit history. They must not automatically create a retry, append a repair
phrase, or alter the frozen user request.

A user-initiated new generation is a new Brain planning pass and may produce a
new direction.

## 5. Bounded Implementation Scope

Expected code scope:

1. `app/shared_capabilities/visual_cluster/human_photorealism.py`
   - preserve the existing shared activation and semantic contract;
   - mark the Brain-authored final direction as required for active execution.

2. `app/llm_brain/prompts.py` and `app/llm_brain/adapter.py`
   - update the existing finalization contract so Brain authors the complete
     direction before returning the canonical prompt;
   - validate its presence and transport without inspecting its wording with
     local rules.

3. The existing human-realism automatic retry dispatch boundary
   - retain review evidence;
   - remove only automatic retry dispatch for human-realism findings.

4. Focused regression tests
   - prove the direction is Brain-owned and reaches the final provider prompt;
   - prove no local keyword or facial-part expansion is used;
   - prove a review finding does not create an automatic retry;
   - cover materially different single-person, multi-person, and
     person-with-product scenes.

No changes are authorized to V1, V2, Sub2API, storage, output binding,
provider protocol, frontend, ecommerce deliverable roles, or scene-specific
prompt branches.

## 6. Acceptance Criteria

- The same shared capability path is used for all visible-person scenes.
- The final Brain-authored direction is present in the canonical provider
  prompt for every active Human Realism job.
- User-owned mood, style, age, identity, and reference channels remain intact.
- No local regex, keyword recipe, facial checklist, or fixed repair phrase is
  added.
- A review finding is recorded but does not automatically create a retry.
- Focused tests pass for the three scene classes above.
- Existing V3 foundation, General, E-Commerce, Photography, Provider, V1,
  V2, and Sub2API regression suites remain green.
- One controlled real-output comparison shows improved skin materiality,
  person-to-person variation, and photographic presence without scene drift.

## 7. Stop Conditions

Stop and re-audit the model if implementation requires any of the following:

- a scene or age-specific branch in shared Human Realism;
- local interpretation of Brain prose;
- provider-side prompt rewriting;
- automatic retries to compensate for missing generation direction;
- changes to V1/V2/Sub2API or deployment configuration.

Until the focused and adjacent tests plus one controlled real-output
comparison pass, do not commit, push, or deploy.
