# PX Mainline Request: Non-Human Subject Identity Foundation Capability

## 1. Request Status

```text
request_id: PHOTOGRAPHY-MAINLINE-002
status: open - blocking animal reference production acceptance
blocking_phase: P4 Animal real-output gate and later P6 continuation
request_owner: Photography Module
implementation_owner: V3 foundation capability owners
```

## 2. Current Mainline Behavior

The shared capability catalog has human portrait identity, product identity and
scene continuity primitives, but no accepted `nonhuman_subject_identity`
capability. The Animal scene director can preserve a declared channel in its
planning contract, but it cannot honestly certify same-pet or same-animal
identity through prompt wording alone.

## 3. Minimal Requested Change

Foundation owners should evaluate and, only after Doc94's three-materially-
different-scenes proof, add a reusable capability with this proposed contract:

```text
capability_id: nonhuman_subject_identity
evidence: one or more user-selected non-human identity reference assets
truth: species, individual markings, facial/head geometry, body proportions,
       coat/feather/scale pattern and other stable individual traits
prompt-owned by default: habitat, action, camera, lighting, color and finish
provider input: identity evidence remains native input images
review: ephemeral comparison only; no persisted biometric-like vectors
retry: bounded identity-local correction only when the rest is acceptable
```

The capability must remain scene-neutral and must not become a pet, dog, cat,
wildlife or Photography-specific shared recipe.

## 4. Validation And Error Semantics

```text
no non-human identity reference -> capability inactive
identity reference with explicit preserve contract -> capability may activate
unsupported or ambiguous evidence -> transparent needs-review/block state
prompt-owned habitat/action/style -> never inherited from identity-only evidence
missing provider fidelity -> block hard same-subject request, never text-only downgrade
retry -> preserve the frozen evidence set and activation plan
```

## 5. API And Persistence Impact

No new client-facing species field is requested. Existing asset/reference-role
contracts should carry evidence only if mainline owners confirm they are typed
and sufficient. If a public or persistence schema change is necessary, it must
be proposed separately before implementation.

Persist only asset references, declared channel ownership and safe audit
metadata. Do not persist biometric embeddings or derived identity vectors.

## 6. Compatibility And Isolation

The inactive capability contributes zero behavior. When active, it must be
usable through shared manifests and template policies rather than a direct
Photography import. Human portrait identity, product identity, General and
E-Commerce behavior must remain unchanged.

## 7. Required Mainline Tests

1. Prove usefulness across at least three materially different scenes.
2. Identity-only evidence preserves stable individual traits without inheriting
   habitat, action, camera, lighting, color or whole-image style.
3. Hard fidelity negotiation blocks unsupported text-only downgrades.
4. Inactive-plugin zero-contribution and hot-removal tests pass.
5. No persisted biometric-like vectors are written.
6. Cross-domain leakage tests contain no species-specific default recipes.
7. Retry preserves the original activation plan and compares candidates.

## 8. Acceptance Evidence Expected

```text
foundation governance approval
three-scene evidence matrix
capability manifest and policy tests
provider fidelity negotiation evidence
ephemeral metric/privacy audit
General/E-Commerce isolation regression
mainline commit hash
```

## 9. Photography Work Paused

Animal text-only shadow planning remains testable, but specific-animal
real-output identity acceptance, production activation and continuation remain
paused. The Photography module will not add a local identity algorithm, prompt
substitute, provider bridge or shared registry entry.
